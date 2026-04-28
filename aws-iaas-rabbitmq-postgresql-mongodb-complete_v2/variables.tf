# Definimos las variables para no hardcodear todo si es posible
variable "vpc_id" {
  default = "vpc-0d97e359cbf13bfef"
}

variable "subnet_id" {
  default = "subnet-0458afa5fb3e8729c"
}

variable "ami_id" {
  default = "ami-02dfbd4ff395f2a1b" # Amazon Linux 2023
}

variable "key_name" {
  default = "vockey"
}

variable "instance_type" {
  default = "t3.micro"
}
