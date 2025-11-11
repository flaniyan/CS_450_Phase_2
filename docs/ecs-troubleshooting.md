## ECS Troubleshooting

- **Symptoms**  
  - Deployments stuck in “In progress” with “service failed to stabilize” message in pipeline or AWS console.  
  - Task count oscillates between 0 and 1, or ALB target stays unhealthy.  
  - Recent tasks in ECS show exit code `1` or `Stopped` state shortly after launch.

- **Immediate Checks**  
  - ECS console → Service → *Events*: look for repeated “deregistered target” or “essential container exited”.  
  - CloudWatch Logs for the task: confirm whether application startup threw an exception (syntax/runtime errors, missing env/secret).  
  - ALB Target Group health: confirm `/health` endpoint returns 200 within configured interval + start period.

- **Common Causes & Fixes**  
  - Application failure (syntax error, uncaught exception) → review logs, fix code, redeploy.  
  - Health check path returning non-200 or timing out → manually curl `/health` locally; adjust start period/timeout if heavy warm-up.  
  - Missing AWS resources (Secrets Manager value, DynamoDB table/index, S3 access) → verify IAM permissions and resource existence.  
  - Network/security-group issues → ensure task subnets have route to internet or required services; confirm security group allows ALB traffic.

- **Useful Commands**  
  - Force new deployment: `aws ecs update-service --cluster validator-cluster --service validator-service --force-new-deployment`.  
  - Wait for stability (built-in waiter): `aws ecs wait services-stable --cluster validator-cluster --services validator-service`.  
  - Describe current status: `aws ecs describe-services --cluster validator-cluster --services validator-service --output table`.  
  - Tail task logs: `aws logs tail /ecs/validator-service --follow`.

- **Preventive Tips**  
  - Run `pytest` locally (with server for integration tests) before pushing.  
  - Start `uvicorn src.entrypoint:app --host 127.0.0.1 --port 8000` to catch startup errors early. If you get an error about bind address increment the port to 8081 and host 127.0.0.2
  - Keep health check endpoint lightweight and returning 200 quickly.

