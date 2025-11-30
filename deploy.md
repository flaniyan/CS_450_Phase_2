Outputs:

artifacts_bucket = "pkg-artifacts"
cloudfront_distribution_id = "EO9M6KHCA4TKM"
cloudfront_domain_name = "d1peqh56nf2wej.cloudfront.net"
cloudfront_url = "https://d1peqh56nf2wej.cloudfront.net"
ddb_tables = {
  "artifacts" = "arn:aws:dynamodb:us-east-1:838693051036:table/artifacts"
  "downloads" = "arn:aws:dynamodb:us-east-1:838693051036:table/downloads"
  "packages" = "arn:aws:dynamodb:us-east-1:838693051036:table/packages"
  "performance_metrics" = "arn:aws:dynamodb:us-east-1:838693051036:table/performance_metrics"
  "tokens" = "arn:aws:dynamodb:us-east-1:838693051036:table/tokens"
  "uploads" = "arn:aws:dynamodb:us-east-1:838693051036:table/uploads"
  "users" = "arn:aws:dynamodb:us-east-1:838693051036:table/users"
}
ecr_repository_url = "838693051036.dkr.ecr.us-east-1.amazonaws.com/validator-service" 
group106_policy_arn = "arn:aws:iam::838693051036:policy/group106_project_policy"      
validator_cluster_arn = "arn:aws:ecs:us-east-1:838693051036:cluster/validator-cluster"
validator_service_url = "http://validator-lb-1665590138.us-east-1.elb.amazonaws.com"

API GATEWAY URL: https://pwuvrbcdu3.execute-api.us-east-1.amazonaws.com/prod