import json
import boto3
import os
import time
import urllib.parse
from typing import Dict, Any

# Initialize AWS clients
sagemaker_runtime = boto3.client('sagemaker-runtime')
s3_client = boto3.client('s3')

# Constants
MAX_WAIT_TIME = 30  # Maximum wait time in seconds
CHECK_INTERVAL = 1  # Time between checks in seconds

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        input_data = prepare_input_data(event)
        invoke_sagemaker_endpoint(input_data)
        output_url = wait_for_output_file(input_data['bucket'], input_data['output'])
        return create_success_response(output_url)
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return create_error_response(str(e))

def prepare_input_data(event: Dict[str, Any]) -> Dict[str, str]:
    s3_event = event['Records'][0]['s3']
    bucket = s3_event['bucket']['name']
    source_key = urllib.parse.unquote_plus(s3_event['object']['key'])
    output_key = f"{os.environ['OUTPUT_PATH']}{source_key}"
    uuid = os.path.basename(source_key).split('.')[0]
    
    return {
        'uuid': uuid,
        'bucket': bucket,
        'source': source_key,
        'output': output_key
    }

def invoke_sagemaker_endpoint(input_data: Dict[str, str]) -> None:
    sagemaker_runtime.invoke_endpoint(
        EndpointName=os.environ['SAGEMAKER_ENDPOINT_NAME'],
        ContentType='application/json',
        Body=json.dumps(input_data)
    )

def wait_for_output_file(bucket: str, output_key: str) -> str:
    start_time = time.time()
    
    while True:
        elapsed_time = time.time() - start_time
        if elapsed_time >= MAX_WAIT_TIME:
            raise TimeoutError(f"Output file not found in S3 after {MAX_WAIT_TIME} seconds: {output_key}")
        
        try:
            s3_client.head_object(Bucket=bucket, Key=output_key)
            output_url = f's3://{bucket}/{output_key}'
            processing_time = round(elapsed_time, 2)  # Round to 2 decimal places
            print(f"Image Processing: Face restoration completed successfully. Processing Time: {processing_time} seconds. Output: {output_url}")
            return output_url
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] != '404':
                raise
        time.sleep(CHECK_INTERVAL)

def create_success_response(output_url: str) -> Dict[str, Any]:
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Image Processing: Face restoration completed successfully.',
            'output_url': output_url
        })
    }

def create_error_response(error_message: str) -> Dict[str, Any]:
    return {
        'statusCode': 500,
        'body': json.dumps({'error': error_message})
    }