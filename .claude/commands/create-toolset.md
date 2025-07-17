You are asked to build a new toolset.

Toolsets provide a set of tools for HolmesGPT (LLM based system) to interact with other systems.

Steps to write a toolset:

# 1. Check existing toolsets

Check holmes/plugins/toolsets for other similar toolsets to see how they are implemented before implementing a new toolset
If implementing a toolset to fetch logs, you need to follow a specific pattern by implementing `BasePodLoggingToolset`

# 2. Choose where to create the new toolset file

Each 'system' should be a folder in `holmes/plugins/toolsets`.
For example, datadog toolsets should be in `holmes/plugins/toolsets/datadog`, aws toolsets in `holmes/plugins/toolsets/aws`, etc.

# 3. Implement the initial toolset config and class

Implement the configuration (if needed). The config is what users use to configure the toolset. This typically includes credentials.
A toolset should not depend on env vars (some existing toolsets depend on end vars but this is not a good practice to follow).

Implement a live healthcheck in a `prerequisite_check()` method. The health check should be contained in a dedicated method that is called by `prerequisite_check()`.

`prerequisite_check()` should also make sure the config has the expected format. This is done by passing the user's config into a pydandic model: `MyToolsetConfigPydanticBaseModel(**config)`.

# 4. Define the tools to implement

Define what tools are required for that toolset. There are three actions that help doing this well:

  a. Look at the user's intention
  b. Analyse similar toolset in the existing toolsets (step 1 above)
  c. Do websearches for the reference documentation of the system that the toolset will connect to. Use subagents.

# 5. Implement one tool at a time

Implement each tool, one at a time. Use subagents.

## Params

Some tools may require parameters. 

- When possible these parameters should have sane default values. Making params optional frees the LLM/HolmesGPT from making decisions about what values should be used. Any default value should be configurable by the user through the toolset config.
- Always prefer using RFC3339 for date inputs, with the possibility to use integers for relative time from "NOW". A good example for this is the date params for the `PodLoggingTool` in `holmes/plugins/toolsets/logging_utils/logging_api.py`.
- Possible param types are string, booleans and numbers.


# 6. Tests

1. Implement a live test. The test should:
  - Depend on env variables (never put any credentials in the code). Ask if you don't have access to the correct env vars.
  - Test the health check (through toolset.check_prerequisites())
  - Test that each tool returns data as expected (verify that the data looks right)
2. Implement integration tests. Because you havew actually verified that the data returned by the system is what you expect, you can now mock its behaviour and implement integration tests for each tool and for different scenarios.