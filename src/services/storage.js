const { S3Client, CreateMultipartUploadCommand, UploadPartCommand, CompleteMultipartUploadCommand, AbortMultipartUploadCommand, PutObjectCommand, HeadObjectCommand, GetObjectCommand } = require("@aws-sdk/client-s3");
const { getSignedUrl } = require("@aws-sdk/s3-request-presigner");

const REGION = process.env.AWS_REGION || "us-east-1";
const ARTIFACTS_BUCKET = process.env.ARTIFACTS_BUCKET || "pkg-artifacts";

const s3 = new S3Client({ region: REGION });

function objectKey(pkgName, version) {
  return `packages/${pkgName}/${version}/package.zip`;
}

function validatorKey(pkgName, version) {
  return `validators/${pkgName}/${version}/validator.js`;
}

async function uploadInit(pkgName, version, options = {}) {
  const Key = objectKey(pkgName, version);
  const cmd = new CreateMultipartUploadCommand({
    Bucket: ARTIFACTS_BUCKET,
    Key,
    ServerSideEncryption: "aws:kms",
    ...options,
  });
  const res = await s3.send(cmd);
  return { uploadId: res.UploadId, key: Key };
}

async function uploadPart(pkgName, version, uploadId, partNumber, body) {
  const Key = objectKey(pkgName, version);
  const cmd = new UploadPartCommand({
    Bucket: ARTIFACTS_BUCKET,
    Key,
    UploadId: uploadId,
    PartNumber: partNumber,
    Body: body,
  });
  const res = await s3.send(cmd);
  return { etag: res.ETag };
}

async function uploadCommit(pkgName, version, uploadId, parts) {
  const Key = objectKey(pkgName, version);
  const cmd = new CompleteMultipartUploadCommand({
    Bucket: ARTIFACTS_BUCKET,
    Key,
    UploadId: uploadId,
    MultipartUpload: {
      Parts: parts.map((p) => ({ ETag: p.etag, PartNumber: p.partNumber })),
    },
  });
  await s3.send(cmd);
}

async function uploadAbort(pkgName, version, uploadId) {
  const Key = objectKey(pkgName, version);
  const cmd = new AbortMultipartUploadCommand({
    Bucket: ARTIFACTS_BUCKET,
    Key,
    UploadId: uploadId,
  });
  await s3.send(cmd);
}

async function getDownloadUrl(pkgName, version, ttlSeconds = 300) {
  const Key = objectKey(pkgName, version);
  // Ensure object exists; throw if not
  await s3.send(new HeadObjectCommand({ Bucket: ARTIFACTS_BUCKET, Key }));
  const url = await getSignedUrl(s3, new GetObjectCommand({ Bucket: ARTIFACTS_BUCKET, Key }), { expiresIn: ttlSeconds });
  return { url, expiresAt: new Date(Date.now() + ttlSeconds * 1000).toISOString() };
}

async function putValidatorScript(pkgName, version, scriptBuffer) {
  const Key = validatorKey(pkgName, version);
  await s3.send(
    new PutObjectCommand({
      Bucket: ARTIFACTS_BUCKET,
      Key,
      Body: scriptBuffer,
      ContentType: "application/javascript",
      ServerSideEncryption: "aws:kms",
    })
  );
}

module.exports = {
  uploadInit,
  uploadPart,
  uploadCommit,
  uploadAbort,
  getDownloadUrl,
  putValidatorScript,
  // deleteValidatorScript could be added later if needed
};


