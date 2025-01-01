

There are 2 types of test cases:

- *ask holmes*: tests the ask holmes functionality. For a single question is supported. back and forth conversation is not supported/tested
- *investigate*: tests the ability of Holmes to investigate issues reported by the alertmanager

## How to write a test case

### ask_holmes

#### 1. Create a test folder

Add a new folder to `tests/llm/fixtures/test_ask_holmes`. For example:

```sh
mkdir tests/llm/fixtures/test_ask_holmes/999_my_test_case
```

#### 2. Add a test case definition

In this folder, add a `test_case.yaml` file:

```yaml
user_prompt: 'Is pod xyz healthy? '
expected_output:
  - pod xyz is running and healthy
retrieval_context:
  - Any element of context. This will inform the evaluation score 'context'
  - These context elements are expected to be present in the output
evaluation: # expected evaluation scores. The test will fail unless the LLM scores at least the following:
  correctness: 0.5 # defaults to 0.3
  context: 0 # defaults to 0
before-test: kubectl apply -f manifest.yaml
after-test: kubectl delete -f manifest.yaml
```

The above file requires a manifest.yaml to deploy resources to your kubernetes cluster. Add that file and any file required by the `before-test` and `after-test` commands.

Here are the possible fields in the `test_case.yaml` yaml file:

| Field             | Type             | Required/optional | Example value                                                               | Description                                                                                                                                                                                                            |
|-------------------|------------------|-------------------|-----------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| user_prompt       | str              | Required          | Is pod xyz healthy?                                                         | The user prompt                                                                                                                                                                                                        |
| expected_output   | str or List[str] | Required          | Yes, pod xyz is healthy. It is running and there are no errors in the logs. | The expected answer from the LLM. This can be a string or a list of expected elements. If it is a string, the response will be scored with 'faithfulness'. Otherwise it is 'correctness'.                              |
| retrieval_context | List[str]        | Optional          | - pod xyz is running and healthy - there are no errors in the logs          | Context that the LLM is expected to have used in its answer. If present, this generates a 'context' score proportional to the number of matching context elements found in the LLM's output.                           |
| evaluation        | Dict[str, float] | Optional          | evaluation: <br/>   faithfulness: 1  <br/>  context: 1  <br/>               | The minimum expected scores. The test will fail unless these are met. Set to 0 for unstable tests.                                                                                                                     |
| before-test       | str              | Optional          | kubectl apply -f manifest.yaml                                              | A command to run before the LLM evaluation. The CWD for this command is the same folder as the fixture. This step is skipped unless `RUN_LIVE` environment variable is set                                             |
| after-test        | str              | Optional          | kubectl delete -f manifest.yaml                                             | A command to run after the LLM evaluation.The CWD for this command is the same folder as the fixture. Typically cleans up any before-test action. This step is skipped unless  `RUN_LIVE`  environment variable is set |
| generate_mocks    | bool             | Optional          | True                                                                        | Whether the test suite should generate mock files. Existing mock files are overwritten.                                                                                                                                |


#### 3. Run the test

Run the following:

```sh
UPLOAD_DATASET=1 RUN_LIVE=1 poetry run pytest ./tests/llm/test_ask_holmes.py -k 999_my_test_case
```

The test may pass or not based on whether the evaluation scores are high enough. If the test fail,

# Environment variables

| Name               | Example                             | Description                                                                                                                            |
|--------------------|-------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| RUN_LIVE           | RUN_LIVE=1                          | Enables the execution of `before-test` and `after-test` commands to setuo any remote resource. This also ignores any mock files.       |
| BRAINTRUST_API_KEY | BRAINTRUST_API_KEY=sk-1dh1...swdO02 | The braintrust API key you get from your account. Log in https://www.braintrust.dev -> top right persona logo -> settings -> API keys. |
| UPLOAD_DATASET     | UPLOAD_DATASET=1                    | Synchronise the dataset from the local machine to braintrust. This is usually safe as datasets are separated by branch name.           |
| EXPERIMENT_ID      | EXPERIMENT_ID=nicolas_gemini_v1     | Override the experiment name in Braintrust. Helps with identifying and comparing experiments. Must be unique across ALL experiments.   |
| MODEL              | MODEL=anthropic/claude-3.5          | The model to use for generation.                                                                                                       |
