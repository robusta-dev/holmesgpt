# Installing HolmesGPT

## In-Cluster Installation (Recommended)

If you use Kubernetes, we recommend installing Holmes + [Robusta](https://github.com/robusta-dev/robusta) as a unified package so you can:

- Analyze Prometheus alerts easily
- Use HolmesGPT in a friendly web UI
- Get started without an OpenAI API Key (but you can bring your own LLM if you prefer)

[Sign up for Robusta SaaS](https://platform.robusta.dev/signup/?utm_source=github&utm_medium=holmesgpt-readme&utm_content=ways_to_use_holmesgpt_section) (Kubernetes cluster required) or contact us about on-premise options.

## CLI Installation

You can install Holmes as a CLI tool and run it on your local machine:

<details>
  <summary>Brew (Mac/Linux)</summary>

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
</details>


<details>
<summary>Docker Container</summary>

Run the prebuilt Docker container `docker.pkg.dev/genuine-flight-317411/devel/holmes`, with extra flags to mount relevant config files (so that kubectl and other tools can access AWS/GCP resources using your local machine's credentials)

```bash
docker run -it --net=host -v ~/.holmes:/root/.holmes -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config us-central1-docker.pkg.dev/genuine-flight-317411/devel/holmes ask "what pods are unhealthy and why?"
```
</details>

<details>

<summary>Pip and Pipx</summary>

You can install HolmesGPT from the latest git version with pip or pipx.

We recommend using pipx because it guarantees that HolmesGPT is isolated from other python packages on your system, preventing dependency conflicts.

First [Pipx](https://github.com/pypa/pipx) (skip this step if you are using pip).

Then install HolmesGPT from git with either pip or pipx:

```
pipx install "https://github.com/robusta-dev/holmesgpt/archive/refs/heads/master.zip"
```

Verify that HolmesGPT was installed by checking the version:

```
holmes version
```

To upgrade HolmesGPT with pipx, you can run:

```
pipx upgrade holmesgpt
```
</details>

<details>

<summary>From Source (Python Poetry)</summary>

First [install poetry (the python package manager)](https://python-poetry.org/docs/#installing-with-the-official-installer)

```
git clone https://github.com/robusta-dev/holmesgpt.git
cd holmesgpt
poetry install --no-root
poetry run python3 holmes.py ask "what pods are unhealthy and why?"
```
</details>

<details>
<summary>From Source (Docker)</summary>

Clone the project from github, and then run:

```bash
cd holmesgpt
docker build -t holmes . -f Dockerfile.dev
docker run -it --net=host -v -v ~/.holmes:/root/.holmes -v ~/.aws:/root/.aws -v ~/.config/gcloud:/root/.config/gcloud -v $HOME/.kube/config:/root/.kube/config holmes ask "what pods are unhealthy and why?"
```
</details>

<details>
<summary>Python API</summary>

You can use Holmes as a library and pass in your own LLM implementation. This is particularly useful if LiteLLM or the default Holmes implementation does not suit you.

See an example implementation [here](examples/custom_llm.py).

</details>
