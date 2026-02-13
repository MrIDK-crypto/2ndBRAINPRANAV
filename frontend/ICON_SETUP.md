# Icon Setup Instructions

## Required Icons

Place all these icons in the `public/` folder of your Next.js project:

### Sidebar Icons:
- `Click.png` - Logo/cursor icon
- `Home.svg` - Knowledge Dashboard icon (keep existing)
- `Training.png` - Training Guides icon
- `Chatbot.png` - ChatBot icon
- `User.png` - Users icon
- `feedback.png` - Feedback icon (replaces Pricing)
- `Integrations.png` - Integrations icon
- `Settings.png` - Settings icon
- `Maya.png` - User avatar

### Quick Action Card Icons:
- `Project.svg` - Summarize Project
- `PPT.svg` - PPT Generation
- `Research.svg` - Research
- `Article.svg` - Generate Article
- `Data.svg` - Data Analytics
- `Code.svg` - Code Explainer

### Chat Input Icons:
- `attach.svg` - Attach button (left side of input)
- `send.svg` - Send button (right side of input)

## Setup Steps:

1. Copy all icon files to the `public/` folder:
```bash
cd /Users/rishitjain/Downloads
cp Click.png Training.png Chatbot.png User.png feedback.png Integrations.png Settings.png Maya.png knowledge-vault-frontend/public/
cp Project.svg PPT.svg Research.svg Article.svg Data.svg Code.svg attach.svg send.svg knowledge-vault-frontend/public/
```

2. Make sure `Home.svg` is also in public:
```bash
cp Home.svg knowledge-vault-frontend/public/
```

3. Restart the dev server:
```bash
cd knowledge-vault-frontend
npm run dev
```

## Changes Made:

1. **Sidebar always visible** - No toggle needed, sidebar is always shown
2. **No line between sidebar and chat** - Seamless integration
3. **Active state styling** - Currently selected item has #FFE2BF background
4. **All icons replaced** - Using your provided icons
5. **Card background color** - Icon backgrounds are #F3F3F3
6. **User message width** - Reduced to max-w-[50%]
7. **Only 2 icons in chatbox** - Attach (left) and Send (right)

## File Structure:
```
knowledge-vault-frontend/
├── public/
│   ├── Click.png
│   ├── Home.svg
│   ├── Training.png
│   ├── Chatbot.png
│   ├── User.png
│   ├── feedback.png
│   ├── Integrations.png
│   ├── Settings.png
│   ├── Maya.png
│   ├── Project.svg
│   ├── PPT.svg
│   ├── Research.svg
│   ├── Article.svg
│   ├── Data.svg
│   ├── Code.svg
│   ├── attach.svg
│   └── send.svg
└── components/
    ├── Sidebar.tsx (updated)
    └── ChatInterface.tsx (updated)
```
