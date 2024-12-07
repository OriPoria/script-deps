# Script-Deps
script-deps is a Python tool designed to streamline the process of creating lightweight, deployable packages for Python scripts. 
With script-deps, you can automatically analyze a script's dependencies and package them, ensuring that your deployment is minimal and optimized.

## How it works
Single command line provided with 3 parameters:
1. Main script path.
2. Root path to collect deps modules to the main script.
3. [Optional] Output path that is the location of the created package, ready for deployment

### How to run
With the following command:
```shell
sdeps <main script path> <path to the root folder to collect modules from> <output path>
```

## Use cases
- Serverless Deployments: Create standalone packages for platforms like AWS Lambda by extracting only the necessary files and dependencies for the handler script.
- Microservices: Package specific scripts from a monolithic application for independent deployment. 
- Standalone Tools: Deploy individual scripts as standalone utilities, removing unnecessary files.
- Optimized Applications: Reduce the size of packaged scripts by including only the required dependencies.