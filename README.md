# module-nec-compliance

HARNESS module: NEC code compliance — code lookups, derating calculations, AFCI/GFCI requirements.

## Entity Contract

- **Produces:** none
- **Consumes:** job, estimate

## Tools

- `check-compliance` — Check a job or estimate for NEC compliance issues
- `lookup-code` — Look up a specific NEC code section
- `calculate-derating` — Calculate wire derating for conduit fill

## Validation

```bash
harness module validate .
```
