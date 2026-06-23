# Official AWS Lambda Python base image (Linux, matches Lambda runtime exactly)
FROM public.ecr.aws/lambda/python:3.12

# Install dependencies
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy the application package.
# main.py lives INSIDE app/ (app/main.py), so we copy the whole app folder.
COPY app ${LAMBDA_TASK_ROOT}/app

# app/main.py defines:  handler = Mangum(app)
# Handler path is therefore "app.main.handler"
CMD ["app.main.handler"]