# Installing HolmesGPT

You can install HolmesGPT in one of the follow three methods:

1. **Standalone**: Run HolmesGPT from your terminal as a CLI tool. Typically installed with **Homebrew or Pip/Pipx**. Ideal for local use, **embedding into shell scripts, or CI/CD pipelines.** (E.g. to analyze why a pipeline deploying to Kubernetes failed.)
2. **Web UIs and TUIs**: HolmesGPT is embedded in several third-party tools, like **Robusta SaaS** and **K9s** (as a plugin).
3. **API**: Embed HolmesGPT in your own app to quickly add **root-cause-analysis functionality and data correlations across multiple sources like logs, metrics, and events**. HolmesGPT exposes an HTTP API and Python SDK, as well as Helm chart to deploy the HTTP server on Kubernetes.


## Standalone

### Brew (Mac/Linux)

1. Add our tap:

```sh
brew tap robusta-dev/homebrew-holmesgpt
```

2. Install holmesgpt:

```sh
brew install holmesgpt
```

3. Check that installation was successful. **This will take a few seconds on the first run - wait patiently.**:

```sh
holmes --help
```

4. Apply an example Pod to Kubernetes with an error that Holmes can investigate:

```sh
kubectl apply -f https://raw.githubusercontent.com/robusta-dev/kubernetes-demos/main/pending_pods/pending_pod_node_selector.yaml
```

5. [Setup an API key](./api-keys.md)

6. Run holmesgpt:

```sh
holmes ask "what is wrong with the user-profile-import pod?"
```


### Docker Container

You can run HolmesGPT via a prebuilt Docker container:

```
docker.pkg.dev/genuine-flight-317411/devel/holmes
```

Here is an example, that mounts relevant config files so that HolmesGPT can use kubectl and other tools:

```bash
docker run -it --net=host -v ~/.holmes:/root/.holmes -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config us-central1-docker.pkg.dev/genuine-flight-317411/devel/holmes ask "what pods are unhealthy and why?"
```

Don't forget to [Setup an API key](./api-keys.md) first.

### Pip and Pipx

You can install HolmesGPT from source with pip or pipx. Pipx is recommended, as it prevents dependency conflicts.

First [Pipx](https://github.com/pypa/pipx)

Then install HolmesGPT from git:

```
pipx install "https://github.com/robusta-dev/holmesgpt/archive/refs/heads/master.zip"
```

Verify that HolmesGPT was installed by checking the version:

```
holmes version
```

[Setup an API key](./api-keys.md) and start testing HolmesGPT:

```
holmes ask "what pods are unhealthy and why?"
```

When new versions of HolmesGPT are released, you can upgrade HolmesGPT with pipx:

```
pipx upgrade holmesgpt
```

### From Source (Python Poetry)

First [install poetry (the python package manager)](https://python-poetry.org/docs/#installing-with-the-official-installer)

```
git clone https://github.com/robusta-dev/holmesgpt.git
cd holmesgpt
poetry install --no-root
```

[Setup an API key](./api-keys.md) and run HolmesGPT:

```
poetry run python3 holmes.py ask "what pods are unhealthy and why?"
```

### From Source (Docker)

Clone the project from github, [setup an API key](./api-keys.md), and then run:

```bash
cd holmesgpt
docker build -t holmes . -f Dockerfile.dev
docker run -it --net=host -v -v ~/.holmes:/root/.holmes -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config holmes ask "what pods are unhealthy and why?"
```

## Web UIs and TUIs

- [Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) - Managed service with web UI
- [K9s Plugin](k9s.md) - Terminal UI for Kubernetes

## API

- [Helm Chart](../helm) - Deploy on Kubernetes
- [Python API](python.md) - Use as a Python library