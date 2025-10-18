# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Security
- **Validator timeout protection**: Added hard wall-time guard to prevent DoS attacks from malicious validator scripts that could hang indefinitely. Implements 5-second timeout with clean error mapping and ECS kill-switch for defense-in-depth.

## [Previous releases]

_No previous releases documented._
