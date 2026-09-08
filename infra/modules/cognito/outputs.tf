output "user_pool_id" {
  description = "Identifier used to build the issuer URL."
  value       = aws_cognito_user_pool.this.id
}

output "user_pool_arn" {
  description = "ARN of the user pool."
  value       = aws_cognito_user_pool.this.arn
}

output "client_id" {
  description = "Audience the application validates tokens against."
  value       = aws_cognito_user_pool_client.web.id
}

output "issuer" {
  description = "OpenID Connect issuer published by the pool."
  value       = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.this.id}"
}

output "jwks_uri" {
  description = "Signing key document the application caches."
  value       = "https://cognito-idp.${data.aws_region.current.name}.amazonaws.com/${aws_cognito_user_pool.this.id}/.well-known/jwks.json"
}

output "hosted_domain" {
  description = "Provider-hosted sign-in domain."
  value       = aws_cognito_user_pool_domain.this.domain
}
