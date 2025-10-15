const express = require('express');
const { DynamoDBClient } = require('@aws-sdk/client-dynamodb');
const { DynamoDBDocumentClient, GetCommand, PutCommand, QueryCommand } = require('@aws-sdk/lib-dynamodb');
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');
const { exec } = require('child_process');
const { promisify } = require('util');
const fs = require('fs').promises;
const path = require('path');
const os = require('os');

const execAsync = promisify(exec);

const app = express();
app.use(express.json());

// AWS Configuration
const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
const ARTIFACTS_BUCKET = process.env.ARTIFACTS_BUCKET || 'pkg-artifacts';
const DDB_TABLE_PACKAGES = process.env.DDB_TABLE_PACKAGES || 'packages';
const DDB_TABLE_DOWNLOADS = process.env.DDB_TABLE_DOWNLOADS || 'downloads';

// AWS Clients
const ddbClient = new DynamoDBClient({ region: AWS_REGION });
const docClient = DynamoDBDocumentClient.from(ddbClient);
const s3Client = new S3Client({ region: AWS_REGION });

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'validator', timestamp: new Date().toISOString() });
});

// Validate package endpoint
app.post('/validate', async (req, res) => {
  try {
    const { pkgName, version, userId, groups = [] } = req.body;
    
    if (!pkgName || !version || !userId) {
      return res.status(400).json({ 
        error: 'Missing required fields: pkgName, version, userId' 
      });
    }

    console.log(`Validating package: ${pkgName}@${version} for user: ${userId}`);

    // 1. Check if package exists in DynamoDB
    const packageKey = `${pkgName}@${version}`;
    const packageResult = await docClient.send(new GetCommand({
      TableName: DDB_TABLE_PACKAGES,
      Key: { pkg_key: packageKey }
    }));

    if (!packageResult.Item) {
      return res.status(404).json({ 
        error: 'Package not found',
        pkgName,
        version 
      });
    }

    const packageData = packageResult.Item;
    
    // 2. Check if package is sensitive and user has access
    if (packageData.is_sensitive) {
      const userGroups = groups || [];
      const packageGroups = packageData.allowed_groups || [];
      
      const hasAccess = packageGroups.some(group => userGroups.includes(group));
      
      if (!hasAccess) {
        // Log unauthorized access attempt
        await docClient.send(new PutCommand({
          TableName: DDB_TABLE_DOWNLOADS,
          Item: {
            event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            pkg_name: pkgName,
            version: version,
            user_id: userId,
            timestamp: new Date().toISOString(),
            status: 'blocked',
            reason: 'insufficient_group_access',
            user_groups: userGroups,
            required_groups: packageGroups
          }
        }));

        return res.status(403).json({ 
          error: 'Access denied',
          reason: 'Package is sensitive and requires group access',
          required_groups: packageGroups,
          user_groups: userGroups
        });
      }
    }

    // 3. Check if validator script exists
    const validatorKey = `validators/${pkgName}/${version}/validator.js`;
    
    try {
      const validatorResult = await s3Client.send(new GetObjectCommand({
        Bucket: ARTIFACTS_BUCKET,
        Key: validatorKey
      }));

      // 4. Download and run validator script
      const validatorScript = await validatorResult.Body.transformToString();
      
      // Create temporary file for validator
      const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'validator-'));
      const validatorPath = path.join(tempDir, 'validator.js');
      
      await fs.writeFile(validatorPath, validatorScript);
      
      // Run validator with package metadata
      const validatorInput = JSON.stringify({
        pkgName,
        version,
        packageData,
        userId,
        groups
      });

      const { stdout, stderr } = await execAsync(
        `node ${validatorPath}`,
        { 
          input: validatorInput,
          timeout: 30000 // 30 second timeout
        }
      );

      // Clean up temp file
      await fs.rm(tempDir, { recursive: true, force: true });

      if (stderr) {
        console.error(`Validator stderr for ${pkgName}@${version}:`, stderr);
      }

      const validationResult = JSON.parse(stdout || '{}');
      
      if (!validationResult.valid) {
        // Log failed validation
        await docClient.send(new PutCommand({
          TableName: DDB_TABLE_DOWNLOADS,
          Item: {
            event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            pkg_name: pkgName,
            version: version,
            user_id: userId,
            timestamp: new Date().toISOString(),
            status: 'blocked',
            reason: 'validation_failed',
            validation_error: validationResult.error || 'Unknown validation error'
          }
        }));

        return res.status(400).json({
          error: 'Validation failed',
          reason: validationResult.error || 'Package validation failed',
          details: validationResult.details
        });
      }

      // 5. Log successful validation
      await docClient.send(new PutCommand({
        TableName: DDB_TABLE_DOWNLOADS,
        Item: {
          event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          pkg_name: pkgName,
          version: version,
          user_id: userId,
          timestamp: new Date().toISOString(),
          status: 'validated',
          validation_result: validationResult
        }
      }));

      res.json({
        valid: true,
        pkgName,
        version,
        validation_result: validationResult,
        message: 'Package validation successful'
      });

    } catch (s3Error) {
      if (s3Error.name === 'NoSuchKey') {
        // No validator script - allow download
        console.log(`No validator script for ${pkgName}@${version}, allowing download`);
        
        await docClient.send(new PutCommand({
          TableName: DDB_TABLE_DOWNLOADS,
          Item: {
            event_id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
            pkg_name: pkgName,
            version: version,
            user_id: userId,
            timestamp: new Date().toISOString(),
            status: 'validated',
            reason: 'no_validator_script'
          }
        }));

        res.json({
          valid: true,
          pkgName,
          version,
          message: 'No validator script found, download allowed'
        });
      } else {
        throw s3Error;
      }
    }

  } catch (error) {
    console.error('Validation error:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});

// Get validation history for a user
app.get('/history/:userId', async (req, res) => {
  try {
    const { userId } = req.params;
    const { limit = 50 } = req.query;

    const result = await docClient.send(new QueryCommand({
      TableName: DDB_TABLE_DOWNLOADS,
      IndexName: 'user-timestamp-index', // We'll need to create this GSI
      KeyConditionExpression: 'user_id = :userId',
      ExpressionAttributeValues: { ':userId': userId },
      ScanIndexForward: false, // Most recent first
      Limit: parseInt(limit)
    }));

    res.json({
      userId,
      history: result.Items || [],
      count: result.Items?.length || 0
    });

  } catch (error) {
    console.error('History error:', error);
    res.status(500).json({
      error: 'Internal server error',
      message: error.message
    });
  }
});

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => {
  console.log(`Validator service running on port ${PORT}`);
  console.log(`AWS Region: ${AWS_REGION}`);
  console.log(`Artifacts Bucket: ${ARTIFACTS_BUCKET}`);
});
