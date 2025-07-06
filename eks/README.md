# EKS Cluster Setup with Terraform

This Terraform configuration sets up an Amazon EKS cluster with:
- EKS cluster
- Node groups
- IAM roles for service accounts
- Kubernetes provider configuration

## Prerequisites
- AWS CLI configured with appropriate credentials
- Terraform installed
- kubectl installed
- AWS EKS IAM Authenticator installed

## Usage

1. Initialize Terraform:
```bash
terraform init
```

2. Review the plan:
```bash
terraform plan
```

3. Apply the configuration:
```bash
terraform apply
```

## Configuration

The configuration includes:
- EKS cluster version 1.27
- Node group with t3.medium instances
- Default node count: 2 nodes
- Auto-scaling between 1-3 nodes
- IAM roles for service accounts

## Connecting to the Cluster

After deployment, you can connect to the cluster using:
```bash
aws eks update-kubeconfig --name <cluster-name> --region <region>
```

## Security Notes
- The cluster is configured with IRSA (IAM Roles for Service Accounts)
- The node group has default security settings
- Consider customizing security settings based on your requirements
