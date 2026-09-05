# Happy path

```
actgate init
actgate propose --tool shell.exec --args '{"cmd":"ls"}' --blast-tags fs.read
# note the intent_id from propose output
actgate dry-run <intent_id>
actgate approve <intent_id>
actgate verify   # exit 0
actgate list
```
