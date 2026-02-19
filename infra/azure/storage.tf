# Azure Data Lake Storage Gen2 Configuration

resource "azurerm_resource_group" "dataforge" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.azure_region
}

resource "azurerm_storage_account" "datalake" {
  name                     = "${var.project_name}datalake${var.environment}"
  resource_group_name      = azurerm_resource_group.dataforge.name
  location                 = azurerm_resource_group.dataforge.location
  account_tier             = "Standard"
  account_replication_type = "GRS"
  https_traffic_only_enabled = true
  is_hns_enabled           = true

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Bronze Container
resource "azurerm_storage_container" "bronze" {
  name                  = "bronze"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

# Silver Container
resource "azurerm_storage_container" "silver" {
  name                  = "silver"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

# Gold Container
resource "azurerm_storage_container" "gold" {
  name                  = "gold"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

# Logs Container
resource "azurerm_storage_container" "logs" {
  name                  = "logs"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

output "storage_account_name" {
  value = azurerm_storage_account.datalake.name
}

output "storage_account_id" {
  value = azurerm_storage_account.datalake.id
}
