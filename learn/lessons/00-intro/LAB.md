# LAB 00 — Primo contatto (60 min)

## Checklist ambiente

```bash
./scripts/learn_physical_design.sh --check
openroad -version
```

## Esplorazione cartelle (20 min)

Naviga manualmente:
```
tools/OpenROAD-flow-scripts/flow/
├── designs/src/gcd/gcd.v          ← RTL
├── designs/nangate45/gcd-tutorial/← config corso
├── platforms/nangate45/           ← PDK
├── scripts/                         ← Tcl fasi
├── results/nangate45/gcd/learn/    ← tuoi artefatti
├── logs/.../learn/
└── reports/.../learn/
```

**Esercizio:** senza guardare README, trova dove finisce il GDS finale.

## Smoke synth (15 min)

```bash
./scripts/learn_physical_design.sh --lesson 00
```

## Leggi obbligatori prima di lezione 01

- [ ] `learn/reference/glossary.md` (almeno sezioni C, F, P, S)
- [ ] `learn/reference/file-formats.md`
- [ ] `learn/workbook/notes-template.md` → crea `mio-quaderno.md`

## Criteri superamento

- [ ] `--check` tutto verde
- [ ] `1_synth.odb` generato in variant `learn`
- [ ] Quaderno creato
