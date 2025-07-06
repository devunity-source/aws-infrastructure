terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.10"
    }
  }
}

provider "aws" {
  region = var.region
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  token                  = data.aws_eks_cluster_auth.this.token
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.1.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = var.vpc_id
  subnet_ids = var.subnet_ids

  manage_aws_auth = true
  enable_irsa     = true

  node_groups = {
    ng1 = {
      desired_capacity = var.node_group_desired_capacity
      max_capacity     = var.node_group_max_capacity
      min_capacity     = var.node_group_min_capacity
      instance_types   = var.node_group_instance_types
      ami_type         = "AL2_x86_64"
      labels = {
        Environment = "dev"
      }
    }
  }

  tags = {
    Terraform = "true"
    Environment = "dev"
  }
}

data "aws_eks_cluster_auth" "this" {
  name = module.eks.cluster_name
}

# IAM Role for Service Accounts
resource "aws_iam_role" "eks_service_account" {
  name = "eks-service-account"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:oidc-provider/oidc.eks.${var.region}.amazonaws.com/id/${module.eks.cluster_id}"
        }
        Condition = {
          StringEquals = {
            "oidc.eks.${var.region}.amazonaws.com/id/${module.eks.cluster_id}:sub": "system:serviceaccount:default:my-service-account"
          }
        }
      }
    ]
  })
}

data "aws_caller_identity" "current" {}
