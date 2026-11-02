import boto3

# Bedrock runtime client in Mumbai region
client = boto3.client("bedrock-runtime", region_name="ap-south-1")

# Nova 2 Lite is served in ap-south-1 through the global inference profile
model_id = "global.amazon.nova-2-lite-v1:0"

# Role and content defined directly in code
messages = [
    {
        "role": "user",
        "content": [{"text": "Explain what is DevOps in one sentense."}],
    }
]

response = client.converse(
    modelId=model_id,
    messages=messages,
    inferenceConfig={"maxTokens": 300, "temperature": 0.1},
)

print(response["output"]["message"]["content"][0]["text"])
