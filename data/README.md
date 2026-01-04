DATA - seed files for dno-crawler

This directory contains project seed data used for development, tests and demos.

Included files (key):
- `seed-data/dnos_enriched.json` - enriched DNO dataset (1,077,730 bytes ≈ 1.08 MB)
  - SHA256: `0b3d82813c2afd9defd4b69b13da9041ff6b0e5cde67313ee94fd32cc7992d84`
- `seed-data/dnos_seed.json` - original seed (618,107 bytes ≈ 0.62 MB)
  - SHA256: `b0bb2c44fd4008389c1a6424980e3b6c12f8b5d6702237be926ff9080393a5d2`
- `seed-data/OeffentlicheMarktakteure.csv` — registry CSV (217,877 bytes ≈ 0.22 MB)
  - SHA256: `94180c89f1cc7e53a85ecb9ff3f03395824065ebeca4d0c3920f3601f4c8563d`

Notes & provenance
- The DNO data is derived from public registry sources (e.g., Marktstammdatenregister) and internal enrichment steps used in this project.
- The `seed-data/marktstammdatenregister/` subfolder is excluded from the repository (it contains raw registry dump files). All other seed files are intentionally tracked in git to keep the project reproducible and CI-friendly.

Usage
- These files are small and safe to include in the repository for reproducibility. If you plan to add much larger or sensitive datasets in the future, consider external hosting (S3, GitHub Releases, Zenodo) or DVC.

Verification
- A `SHA256SUMS` file is provided at `data/seed-data/SHA256SUMS`. To verify all files at once (run from the repository root):

```
sha256sum -c data/seed-data/SHA256SUMS
```

- To verify a single file, run (example):

```
echo "0b3d82813c2afd9defd4b69b13da9041ff6b0e5cde67313ee94fd32cc7992d84  data/seed-data/dnos_enriched.json" | sha256sum -c -
```

- If the checksum check fails, do not use the file and contact the data maintainer.

If you need the full provenance, licensing details, or want me to add a download script or a sample file, I can add those next.