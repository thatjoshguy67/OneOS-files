# OneOS files

The package set files the [OneOS](https://github.com/fahadalijaved/OneOS) app downloads when it sets up a
system on a phone. Each is a release asset named by its SHA-256; the app picks the files its phone's system
needs and checks every one against the hash it carries before using it.

They are not meant for downloading by hand. Get the app from
[OneOS releases](https://github.com/fahadalijaved/OneOS/releases/latest).


## Fold8 LineageOS patches

The experimental release now includes `f8-lineage.json` for LineageOS 24 on the
Galaxy Z Fold8. [Source patch, scope and verification](patches/lineage-f8/README.md).
The source patch applies to upstream OneOS 0.5.09 (`b10515c`).

The updated app discovers compatible per-device/OS manifests from this fork.
One app update is needed to add discovery and the Lineage payload roles; future
compatible manifests appear without another update. Choose this source and use
Update/Repair before booting. Payloads have static validation; a physical guest
boot and hinge/gesture checks are still pending.
