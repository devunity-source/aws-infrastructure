# AWS Infrastructure with Terraform

This Terraform configuration sets up a basic AWS infrastructure with:
- VPC
- Public Subnet
- Internet Gateway
- Security Group
- EC2 Instance
- Application Load Balancer

## Prerequisites
- AWS CLI configured with appropriate credentials
- Terraform installed

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

## Resources Created
- VPC with CIDR 10.0.0.0/16
- Public Subnet with CIDR 10.0.1.0/24
- Internet Gateway
- Security Group with HTTP/HTTPS/SSH access
- EC2 Instance (t2.micro)
- Application Load Balancer
- Target Group and Listener

## Security Notes
- The security group currently allows SSH access from anywhere (0.0.0.0/0). Consider restricting this to your IP address for better security.
- The load balancer is configured as public (internet-facing).

## Blog

`blog/` holds the Protocloud Reviews tech blog (Astro static site, Google AdSense, Amazon affiliate).
See [blog/README.md](blog/README.md) for setup, writing posts and deployment.
