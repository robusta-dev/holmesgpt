# Getting an LLM API Key for HolmesGPT

If you use HolmesGPT with Robusta SaaS, you can start using HolmesGPT right away, without an API Key like OpenAI.

If you're running HolmesGPT standalone, you'll need to bring your own API Key for an AI model of your choice.

The most popular LLM provider is OpenAI, but you can use most [LiteLLM-compatible](https://docs.litellm.ai/docs/providers/) AI models with HolmesGPT. To use an LLM, set `--model` (e.g. `gpt-4o` or `bedrock/anthropic.claude-3-5-sonnet-20240620-v1:0`) and `--api-key` (if necessary). Depending on the provider, you may need to set environment variables too.

**Instructions for popular LLMs:**

## OpenAI

To work with OpenAI's GPT 3.5 or GPT-4 models you need a paid [OpenAI API key](https://help.openai.com/en/articles/4936850-where-do-i-find-my-openai-api-key).

**Note**: This is different from being a "ChatGPT Plus" subscriber.

Pass your API key to holmes with the `--api-key` cli argument. Because OpenAI is the default LLM, the `--model` flag is optional for OpenAI (gpt-4o is the default).

```
holmes ask --api-key="..." "what pods are crashing in my cluster and why?"
```

If you prefer not to pass secrets on the cli, set the OPENAI_API_KEY environment variable or save the API key in a HolmesGPT config file.

## Anthropic

To use Anthropic's Claude models, you need an [Anthropic API key](https://support.anthropic.com/en/articles/8114521-how-can-i-access-the-anthropic-api).

Set the `ANTHROPIC_API_KEY` environment variable and specify the model:

```bash
export ANTHROPIC_API_KEY="your-anthropic-api-key"
holmes ask "what pods are unhealthy and why?" --model="anthropic/claude-3-opus-20240229"
```

You can also pass the API key directly via the CLI:

```bash
holmes ask "what pods are unhealthy and why?" --model="anthropic/claude-3-opus-20240229" --api-key="your-anthropic-api-key"
```

Available models include `claude-3-opus-20240229`, `claude-3-sonnet-20240229`, and `claude-3-haiku-20240307`.


## Azure OpenAI

To work with Azure AI, you need an [Azure OpenAI resource](https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource) and to set the following environment variables:

* AZURE_API_VERSION - e.g. 2024-02-15-preview
* AZURE_API_BASE - e.g. https://my-org.openai.azure.com/
* AZURE_API_KEY (optional) - equivalent to the `--api-key` cli argument

Set those environment variables and run:

```bash
holmes ask "what pods are unhealthy and why?" --model=azure/<DEPLOYMENT_NAME> --api-key=<API_KEY>
```

Refer [LiteLLM Azure docs ↗](https://litellm.vercel.app/docs/providers/azure) for more details.

## AWS Bedrock

Before running the below command you must run `pip install boto3>=1.28.57` and set the following environment variables:

* `AWS_REGION_NAME`
* `AWS_ACCESS_KEY_ID`
* `AWS_SECRET_ACCESS_KEY`

If the AWS cli is already configured on your machine, you may be able to find those parameters with:

```console
cat ~/.aws/credentials ~/.aws/config
```

Once everything is configured, run:
```console
holmes ask "what pods are unhealthy and why?" --model=bedrock/<MODEL_NAME>
```

Be sure to replace `MODEL_NAME` with a model you have access to - e.g. `anthropic.claude-3-5-sonnet-20240620-v1:0`. To list models your account can access:

```
aws bedrock list-foundation-models --region=us-east-1
```

Note that different models are available in different regions. For example, Claude Opus is only available in us-west-2.

Refer to [LiteLLM Bedrock docs ↗](https://litellm.vercel.app/docs/providers/bedrock) for more details.

## Ollama

Ollama is supported, but buggy. We recommend using other models if you can, until Ollama tool-calling capabilities improve.
Specifically, Ollama often calls tools with non-existent or missing parameters.

If you'd like to try using Ollama anyway, see below:
```
export OLLAMA_API_BASE="http://localhost:11434"
holmes ask "what pods are unhealthy in my cluster?" --model="ollama_chat/llama3.1"
```

You can also connect to Ollama in the standard OpenAI format (this should be equivalent to the above):

```
# note the v1 at the end
export OPENAI_API_BASE="http://localhost:11434/v1"
# holmes requires OPENAPI_API_KEY to be set but value does not matter
export OPENAI_API_KEY=123
holmes ask "what pods are unhealthy in my cluster?" --model="openai/llama3.1"
```
## Gemini

To use Gemini, set the `GEMINI_API_KEY` environment variable as follows:

```bash
export GEMINI_API_KEY="your-gemini-api-key"
```

Once the environment variable is set, you can run the following command to interact with Gemini:

```bash
holmes ask "what pods are unhealthy and why?" --model=gemini/<MODEL_NAME>
```

Be sure to replace `MODEL_NAME` with a model you have access to - e.g., `gemini-pro`,`gemini/gemini-1.5-flash`, etc.

## Google Vertex AI

To use Vertex AI with Gemini models, set the following environment variables:

```bash
export VERTEXAI_PROJECT="your-project-id"
export VERTEXAI_LOCATION="us-central1"
export GOOGLE_APPLICATION_CREDENTIALS="path/to/your/service_account_key.json"
```

Once the environment variables are set, you can run the following command to interact with Vertex AI Gemini models:

```bash
poetry run python holmes.py ask "what pods are unhealthy and why?" --model "vertex_ai/<MODEL_NAME>"
```

Be sure to replace `MODEL_NAME` with a model you have access to - e.g., `gemini-pro`,`gemini-2.0-flash-exp`, etc.
Ensure you have the correct project, location, and credentials for accessing the desired Vertex AI model.

## Other OpenAI-compatible models

You will need an LLM with support for function-calling (tool-calling).

* Set the environment variable for your URL with `OPENAI_API_BASE`
* Set the model as `openai/<your-model-name>` (e.g., `llama3.1:latest`)
* Set your API key (if your URL doesn't require a key, then add a random value for `--api-key`)

```bash
export OPENAI_API_BASE=<URL_HERE>
holmes ask "what pods are unhealthy and why?" --model=openai/<MODEL_NAME> --api-key=<API_KEY_HERE>
```

**Important: Please verify that your model and inference server support function calling! HolmesGPT is currently unable to check if the LLM it was given supports function-calling or not. Some models that lack function-calling capabilities will  hallucinate answers instead of reporting that they are unable to call functions. This behaviour depends on the model.**

In particular, note that [vLLM does not yet support function calling](https://github.com/vllm-project/vllm/issues/1869), whereas [llama-cpp does support it](https://github.com/abetlen/llama-cpp-python?tab=readme-ov-file#function-calling).

## Additional LLM Configuration:

### Trusting custom Certificate Authority (CA) certificate

If your llm provider url uses a certificate from a custom CA, in order to trust it, base-64 encode the certificate, and store it in an environment variable named <b>CERTIFICATE</b>
