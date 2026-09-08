# Operator accounts are created by an administrator. There is no self-service
# sign-up, and the pool holds no customer identities.
resource "aws_cognito_user_pool" "this" {
  name                     = "${var.name_prefix}-users"
  user_pool_tier           = var.tier
  deletion_protection      = var.deletion_protection
  auto_verified_attributes = ["email"]
  username_attributes      = ["email"]
  mfa_configuration        = "OPTIONAL"

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 3
  }

  # Declared so enabling multi-factor authentication later is a configuration
  # change rather than a replacement of the pool.
  software_token_mfa_configuration {
    enabled = true
  }

  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 5
      max_length = 254
    }
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = merge(var.tags, { Name = "${var.name_prefix}-users" })
}

resource "aws_cognito_user_pool_domain" "this" {
  domain       = var.domain_prefix
  user_pool_id = aws_cognito_user_pool.this.id
}

# Authorization code with PKCE. The browser never holds a client secret, and
# the implicit flow stays off so a token is never returned in a redirect URL.
resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.name_prefix}-web"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret                      = false
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]

  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls

  explicit_auth_flows = ["ALLOW_REFRESH_TOKEN_AUTH"]

  access_token_validity  = var.access_token_validity_minutes
  id_token_validity      = var.id_token_validity_minutes
  refresh_token_validity = var.refresh_token_validity_days

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  # A rotated refresh token limits what a leaked one is worth.
  enable_token_revocation       = true
  prevent_user_existence_errors = "ENABLED"
}

# Group membership is what the application reads to authorize an action.
resource "aws_cognito_user_group" "roles" {
  for_each     = toset(var.roles)
  name         = each.value
  user_pool_id = aws_cognito_user_pool.this.id
  description  = "Grants the ${each.value} role in the operations application."
}

data "aws_region" "current" {}
