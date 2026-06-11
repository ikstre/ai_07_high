# Vendored OmniServe vision decoder

`pipeline.py` is vendored verbatim from NAVER-Cloud-HyperCLOVA-X/OmniServe
(`decoder/vision/track_b/pipeline.py`, Apache-2.0) to decode HyperCLOVAX-SEED-Omni-8B
discrete image tokens into RGB images without the full OmniServe Docker stack.

It defines `VisionTokenToImagePipeline` (diffusers custom pipeline): discrete vision
tokens (729 ids, 0..65535) -> token_embedder -> VisionTransformer DiT -> FLUX VAE -> image.
Loaded against the HF `decoder/vision/` weights via `custom_pipeline=`.
