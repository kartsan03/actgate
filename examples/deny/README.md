# Deny / fail path

```
actgate init
actgate propose --tool fs.write --args '{"path":"/etc/passwd"}' --blast-tags fs.write
actgate deny <intent_id> --reason "path too sensitive"
# exits 1

# Broken chain also fails verify:
# (manually corrupt entry_hash in .actgate/ledger.jsonl)
actgate verify   # exits 1
```
