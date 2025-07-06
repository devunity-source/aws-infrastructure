variable "region" {
  description = "The AWS region to deploy the EKS cluster in"
  type        = string
  default     = "eu-central-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "dev-eks-cluster"
}

variable "cluster_version" {
  description = "Version of Kubernetes to use"
  type        = string
  default     = "1.27"
}

variable "vpc_id" {
  description = "ID of the VPC to deploy the EKS cluster in"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs to deploy the EKS cluster in"
  type        = list(string)
}

variable "node_group_desired_capacity" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "node_group_max_capacity" {
  description = "Maximum number of worker nodes"
  type        = number
  default     = 3
}

variable "node_group_min_capacity" {
  description = "Minimum number of worker nodes"
  type        = number
  default     = 1
}

variable "node_group_instance_types" {
  description = "Instance types for worker nodes"
  type        = list(string)
  default     = ["t3.medium"]
}
