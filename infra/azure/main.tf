terraform {
  required_version = ">= 1.0"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "dataforge-terraform-rg"
    storage_account_name = "dataforgetfstate"
    container_name       = "tfstate"
    key                  = "prod.tfstate"
  }
}

provider "azurerm" {
  features {}
}

variable "azure_region" {
  default = "eastus"
}

variable "environment" {
  default = "prod"
}

variable "project_name" {
  default = "dataforge"
}
