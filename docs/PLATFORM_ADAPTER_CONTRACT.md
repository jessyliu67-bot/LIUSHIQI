# Platform Adapter Contract

## Shared records

- Entity records retain the supplied legal name, registration jurisdiction, address, phone, and provenance for source documents. Local extraction is not an official registry check.
- Store records retain stable store codes and template identities. Domains and support emails are store-specific.
- Policy packages contain seven logical documents with platform-specific file formats and publishing paths.
- Product records retain the original CSV fields, variants, SKUs, prices, image references, and source mappings.
- Delivery reports record the selected platform, source/template identity, validation findings, and generated archive hash.

## Shopify

- V35 source bundles contain one Shopify CSV, four Liquid files, and seven policy documents.
- The normal bundle is a source-resource export; it is not a complete installable Shopify theme package.
- Product CSV validation reads the actual headers, including Shopify's URL handle field and source SKU/image columns.
- Policy pages and footer links require the merchant's confirmed page handles and actual business details before production publication.

## SHOPLINE

- V35 source bundles contain one Shopify-migration-format CSV, three SLINE files, and seven Word/TXT policy documents.
- SHOPLINE theme files are SLINE and remain independent from Shopify Liquid.
- The homepage reads eight configured product handles using native SLINE all_products first. The bundle retains a configured fallback for stores where the native result is unavailable.
- Static validation checks each configured handle against published rows in the paired CSV and rejects an Ajax-only loader.
- Static checks do not prove a real SHOPLINE store imports the CSV, renders the theme, loads remote images, or publishes policies correctly. Verify those behaviors in an authorized test store before treating the integration as live-ready.

## Release gates

- Keep the V35 source archive immutable and compare SHA-256 before upgrades.
- Preserve all 300 mappings across both platform exports.
- Fail release validation on missing resources, handle mismatch, missing policy files, invalid CSV structure, or failed CI.
- Report static, simulated, Windows-package, and live-platform results separately.
