const { Router } = require("express");
const router = Router();
const auth = require("../services/auth");
const jwt = require("jsonwebtoken");

function required(value, name) {
  if (!value) {
    const err = new Error(`${name} is required`);
    err.status = 400;
    throw err;
  }
}

// Register new user (admin only)
router.post("/register", async (req, res, next) => {
  try {
    const { username, password, roles = [], groups = [] } = req.body || {};
    required(username, "username");
    required(password, "password");
    
    const user = await auth.createUser(username, password, roles, groups);
    res.status(201).json({
      userId: user.userId,
      username: user.username,
      roles: user.roles,
      groups: user.groups
    });
  } catch (e) {
    next(e);
  }
});

// Login and get token
router.post("/login", async (req, res, next) => {
  try {
    const { username, password } = req.body || {};
    required(username, "username");
    required(password, "password");
    
    const user = await auth.authenticateUser(username, password);
    const token = auth.generateToken(user.userId, user.roles, user.groups);
    const expiresAt = new Date(Date.now() + 10 * 60 * 60 * 1000); // 10 hours
    
    await auth.storeToken(token, user.userId, expiresAt);
    
    res.json({
      token,
      expiresAt: expiresAt.toISOString(),
      userId: user.userId,
      username: user.username,
      roles: user.roles,
      groups: user.groups,
      remainingUses: auth.MAX_USES
    });
  } catch (e) {
    next(e);
  }
});

// Validate token and get user info
router.get("/me", async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    const token = auth.extractTokenFromHeader(authHeader);
    
    // Verify JWT signature and expiration
    const decoded = jwt.verify(token, auth.JWT_SECRET);
    
    // Check usage count in DynamoDB
    const tokenInfo = await auth.validateAndConsumeToken(token);
    
    res.json({
      userId: decoded.sub,
      roles: decoded.roles,
      groups: decoded.groups,
      remainingUses: tokenInfo.remainingUses
    });
  } catch (e) {
    next(e);
  }
});

// Revoke token (logout)
router.post("/logout", async (req, res, next) => {
  try {
    const authHeader = req.headers.authorization;
    const token = auth.extractTokenFromHeader(authHeader);
    
    await auth.revokeToken(token);
    res.status(204).end();
  } catch (e) {
    next(e);
  }
});

module.exports = router;
