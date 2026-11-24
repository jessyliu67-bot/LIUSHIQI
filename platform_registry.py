"""Product/platform capability contract. No implied Shopify/SHOPLINE interchangeability."""
from __future__ import annotations
CAPABILITIES={
 'shopify':{
   'display_name':'Shopify',
   'source_format':'Shopify CSV with 4 Liquid modules and 7 policy files',
   'source_inspection':'available',
   'policy_offline_filling':'available',
   'source_bundle_export':'available',
   'complete_theme_build':'not_implemented',
   'live_publishing':'not_connected',
   'live_compliance_verification':'not_connected',
   'notes':'四份Liquid为现有装修模块，不构成已验证的完整Shopify主题。'},
 'shopline':{
   'display_name':'SHOPLINE',
   'target_theme_version':'OS 3.0 / Sline (subject to store confirmation)',
   'source_inspection':'available',
   'policy_offline_filling':'available_from_V23',
   'product_import_mapping':'V35_shopify_migration_csv_available_not_live_tested',
   'theme_conversion':'V35_three_sline_components_available_not_live_tested',
   'policy_publication':'offline_DOCX_TXT_only',
   'live_publishing':'not_connected',
   'live_compliance_verification':'not_connected',
   'notes':'V35保留SLINE、一份迁移商品CSV及Word/TXT政策，但需在目标SHOPLINE店铺验证导入和发布。'
 }
}

def platform_capabilities():return {'platforms':CAPABILITIES,'note':'这是真实实现状态，不是计划功能的完成声明。'}
