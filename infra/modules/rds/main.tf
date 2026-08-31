resource "aws_db_subnet_group" "this" {
  name       = "${var.name_prefix}-postgres"
  subnet_ids = var.subnet_ids
  tags       = merge(var.tags, { Name = "${var.name_prefix}-postgres" })
}

resource "aws_db_instance" "this" {
  identifier                 = "${var.name_prefix}-postgres"
  engine                     = "postgres"
  engine_version             = var.engine_version
  instance_class             = var.instance_class
  allocated_storage          = var.allocated_storage
  db_name                    = var.db_name
  username                   = var.username
  password                   = var.password
  db_subnet_group_name       = aws_db_subnet_group.this.name
  vpc_security_group_ids     = var.vpc_security_group_ids
  multi_az                   = var.multi_az
  storage_encrypted          = true
  publicly_accessible        = false
  backup_retention_period    = var.backup_retention_period
  deletion_protection        = !var.skip_final_snapshot
  skip_final_snapshot        = var.skip_final_snapshot
  auto_minor_version_upgrade = true
  apply_immediately          = false
  tags                       = merge(var.tags, { Name = "${var.name_prefix}-postgres" })
}
