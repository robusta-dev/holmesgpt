from langsmith import Client, evaluate
client = Client()

def test_langsmith():
    # Define dataset: these are your test cases
    dataset_name = "Sample Dataset"
    dataset = client.create_dataset(dataset_name, description="A sample dataset in LangSmith.")
    client.create_examples(
        inputs=[
            {"postfix": "to LangSmith"},
            {"postfix": "to Evaluations in LangSmith"},
        ],
        outputs=[
            {"output": "Welcome to LangSmith"},
            {"output": "Welcome to Evaluations in LangSmith"},
        ],
        dataset_id=dataset.id,
    )

    # Define your evaluator
    def exact_match(run, example):
        return {"score": run.outputs["output"] == example.outputs["output"]}

    experiment_results = evaluate(
        lambda input: "Welcome " + input['postfix'], # Your AI system goes here
        data=dataset_name, # The data to predict and grade over
        evaluators=[exact_match], # The evaluators to score the results
        experiment_prefix="MAIN-2356", # The name of the experiment
        metadata={
            "version": "1.0.0",
            "revision_id": "beta"
        },
    )

    print(experiment_results)
    assert False
