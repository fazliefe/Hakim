## HAKİM Product Charter

HAKİM is a **legal working environment**, not an AI marketing site and not a chat app.

- Professional, dense, trustworthy, source-first.
- Dark and light modes are first-class.
- Motion is restrained. Prefer no animation over decoration.
- Chat is one input method. The product is the workspace around it.
- Every claim in the main pane must keep its sources visible in the inspector.
- Neon purple/pink AI gradients, oversized chat bubbles, and glow effects are forbidden.

### Interaction model

```
┌────────────────────────────────────────────────────────────┐
│ HAKİM          Araştırma  Evrak  Süreç  İşlem     Profil   │
├───────────────┬──────────────────────────┬─────────────────┤
│ Navigation    │    Main workspace        │ Source / Detail │
│ Dosyalar      │                          │ Inspector       │
│ Araştırmalar  │                          │                 │
│ Geçmiş        │                          │                 │
├───────────────┴──────────────────────────┴─────────────────┤
│ Retrieval trace / status / active sources                  │
└────────────────────────────────────────────────────────────┘
```

- Left: files, researches, history.
- Center: current module (research, document, process, action).
- Right: source inspector — always available, never a modal afterthought.
- Bottom: retrieval trace and system status.

### Product modules

| Route | Page override |
|-------|----------------|
| Araştırma | `pages/research.md` |
| Evrak | `pages/document.md` |
| Süreç | `pages/process.md` |
| İşlem | `pages/action.md` |
| Graph view | `pages/graph.md` |
| Source explorer | `pages/source-explorer.md` |
