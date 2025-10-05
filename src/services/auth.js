const jwt = require("jsonwebtoken");
const bcrypt = require("bcryptjs");
const { DynamoDBClient } = require("@aws-sdk/client-dynamodb");
const { DynamoDBDocumentClient, GetCommand, PutCommand, UpdateCommand, DeleteCommand } = require("@aws-sdk/lib-dynamodb");

const REGION = process.env.AWS_REGION || "us-east-1";
const USERS_TABLE = process.env.DDB_TABLE_USERS || "users";
const TOKENS_TABLE = process.env.DDB_TABLE_TOKENS || "tokens";
const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-change-in-production";
const JWT_EXPIRES_IN = "10h";
const MAX_USES = 1000;

const client = new DynamoDBClient({ region: REGION });
const docClient = DynamoDBDocumentClient.from(client);

async function hashPassword(password) {
  return bcrypt.hash(password, 10);
}

async function verifyPassword(password, hash) {
  return bcrypt.compare(password, hash);
}

function generateToken(userId, roles = [], groups = []) {
  return jwt.sign(
    { sub: userId, roles, groups },
    JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );
}

async function createUser(username, password, roles = [], groups = []) {
  const userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  const passwordHash = await hashPassword(password);
  
  await docClient.send(new PutCommand({
    TableName: USERS_TABLE,
    Item: {
      user_id: userId,
      username,
      password_hash: passwordHash,
      roles,
      groups,
      created_at: new Date().toISOString()
    }
  }));
  
  return { userId, username, roles, groups };
}

async function authenticateUser(username, password) {
  // Query by username instead of user_id
  const { ScanCommand } = require("@aws-sdk/lib-dynamodb");
  const result = await docClient.send(new ScanCommand({
    TableName: USERS_TABLE,
    FilterExpression: "username = :username",
    ExpressionAttributeValues: { ":username": username }
  }));
  
  if (!result.Items || result.Items.length === 0) {
    throw new Error("User not found");
  }
  
  const user = result.Items[0];
  const isValid = await verifyPassword(password, user.password_hash);
  if (!isValid) {
    throw new Error("Invalid password");
  }
  
  return {
    userId: user.user_id,
    username: user.username,
    roles: user.roles || [],
    groups: user.groups || []
  };
}

async function storeToken(tokenId, userId, expiresAt) {
  await docClient.send(new PutCommand({
    TableName: TOKENS_TABLE,
    Item: {
      token_id: tokenId,
      user_id: userId,
      remaining_uses: MAX_USES,
      exp_ts: Math.floor(expiresAt.getTime() / 1000) // TTL in seconds
    }
  }));
}

async function validateAndConsumeToken(tokenId) {
  const result = await docClient.send(new GetCommand({
    TableName: TOKENS_TABLE,
    Key: { token_id: tokenId }
  }));
  
  if (!result.Item) {
    throw new Error("Token not found");
  }
  
  if (result.Item.remaining_uses <= 0) {
    throw new Error("Token exhausted");
  }
  
  // Decrement usage count
  await docClient.send(new UpdateCommand({
    TableName: TOKENS_TABLE,
    Key: { token_id: tokenId },
    UpdateExpression: "SET remaining_uses = remaining_uses - :dec",
    ConditionExpression: "remaining_uses > :zero",
    ExpressionAttributeValues: {
      ":dec": 1,
      ":zero": 0
    }
  }));
  
  return {
    userId: result.Item.user_id,
    remainingUses: result.Item.remaining_uses - 1
  };
}

async function revokeToken(tokenId) {
  await docClient.send(new DeleteCommand({
    TableName: TOKENS_TABLE,
    Key: { token_id: tokenId }
  }));
}

function extractTokenFromHeader(authHeader) {
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    throw new Error("Missing or invalid Authorization header");
  }
  return authHeader.substring(7);
}

module.exports = {
  createUser,
  authenticateUser,
  generateToken,
  storeToken,
  validateAndConsumeToken,
  revokeToken,
  extractTokenFromHeader,
  JWT_SECRET,
  JWT_EXPIRES_IN,
  MAX_USES
};
