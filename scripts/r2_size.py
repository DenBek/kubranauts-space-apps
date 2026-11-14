import boto3, os

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['CF_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET"],
    region_name="auto",
)

total, per_folder = 0, {}
for page in s3.get_paginator("list_objects_v2").paginate(Bucket="firms-data"):
    for obj in page.get("Contents", []):
        folder = obj["Key"].rsplit("/", 1)[0]
        per_folder[folder] = per_folder.get(folder, 0) + obj["Size"]
        total += obj["Size"]

for folder, size in sorted(per_folder.items()):
    print(f"{folder:28s} {size / 1e9:6.2f} GB")
print(f"{'TOTAL':28s} {total / 1e9:6.2f} GB   (free tier: 10 GB)")