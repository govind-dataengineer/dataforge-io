# Azure Databricks for Spark Compute

resource "azurerm_databricks_workspace" "dataforge" {
  name                = "${var.project_name}-${var.environment}-workspace"
  resource_group_name = azurerm_resource_group.dataforge.name
  location            = azurerm_resource_group.dataforge.location
  sku                 = "premium"

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Azure SQL Database for Metadata
resource "azurerm_mssql_server" "metadata" {
  name                         = "${var.project_name}-metadata-${var.environment}"
  resource_group_name          = azurerm_resource_group.dataforge.name
  location                     = azurerm_resource_group.dataforge.location
  version                      = "12.0"
  administrator_login          = "sqladmin"
  administrator_login_password = var.sql_password

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

resource "azurerm_mssql_database" "metadata" {
  name           = "dataforge_metadata"
  server_id      = azurerm_mssql_server.metadata.id
  collation      = "SQL_Latin1_General_CP1_CI_AS"
  license_type   = "LicenseIncluded"
  max_size_gb    = 32
  sku_name       = "Basic"

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Azure Key Vault for Secrets
resource "azurerm_key_vault" "vault" {
  name                = "${var.project_name}-vault-${var.environment}"
  resource_group_name = azurerm_resource_group.dataforge.name
  location            = azurerm_resource_group.dataforge.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    key_permissions = [
      "Get",
      "List",
    ]

    secret_permissions = [
      "Get",
      "List",
      "Set",
      "Delete",
    ]

    storage_permissions = [
      "Get",
      "List",
    ]
  }

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

data "azurerm_client_config" "current" {}

variable "sql_password" {
  type      = string
  sensitive = true
}

output "databricks_workspace_id" {
  value = azurerm_databricks_workspace.dataforge.workspace_id
}

output "key_vault_id" {
  value = azurerm_key_vault.vault.id
}
