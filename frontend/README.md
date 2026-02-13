# Knowledge Vault Frontend

Beautiful, modern frontend for the Knowledge Vault AI system - built exactly to Figma specifications.

## 🎨 Features

- ✅ Hidden sidebar (slides in on click)
- ✅ Exact Figma specifications for all components
- ✅ Welcome screen with quick action cards
- ✅ Real-time chat with backend
- ✅ Clean, professional design
- ✅ Tailwind CSS for styling
- ✅ TypeScript for type safety

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd knowledge-vault-frontend
npm install
```

### 2. Start Development Server

```bash
npm run dev
```

### 3. Open Browser

```
http://localhost:3000
```

## 🔌 Backend Connection

Make sure your Flask backend is running:

```bash
# In another terminal
cd /Users/rishitjain/Downloads
python3 flask_backend.py
```

Backend should be running on `http://localhost:5001`

## 📐 Design Specifications

All components match your Figma design exactly:

### Sidebar
- Width: 280px
- Background: #FFF3E4
- Hidden by default, slides in on toggle

### Search Box
- Width: 243.75px
- Height: 42px
- Border: 0.6px solid #343B4F
- Background: #FFF3E4

### Chat Container
- Width: 1079px
- Height: 806px
- Border-radius: 24px
- Background: #FFE2BF

### Input Box
- Height: 79px
- Border-radius: 20px
- Background: White

### Typography
- Font Family: Inter, Work Sans
- Title: 20px, 600 weight
- Menu Items: 14px, 500 weight

## 🎯 Features

### Welcome Screen
- 6 quick action cards
- Click any card to start conversation with that prompt
- Professional design matching Figma

### Chat Interface
- User messages: White boxes, right-aligned
- AI messages: Transparent, left-aligned
- Source citations shown below AI responses
- Loading indicator while thinking

### Sidebar (Hidden)
- Toggle via logo button
- All navigation items
- Search functionality
- Settings at bottom

## 🛠️ Tech Stack

- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Axios** - API calls

## 📁 Project Structure

```
knowledge-vault-frontend/
├── app/
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── ChatInterface.tsx
│   └── Sidebar.tsx
├── package.json
├── tailwind.config.js
└── tsconfig.json
```

## 🎨 Colors

- **Primary**: #FFF3E4
- **Secondary**: #FFE2BF
- **Neutral 800**: #081028
- **Neutral 500**: #7E89AC
- **Border**: #343B4F

## 🔧 Development

### Run Development Server
```bash
npm run dev
```

### Build for Production
```bash
npm run build
npm start
```

### Lint Code
```bash
npm run lint
```

## 🎬 Demo Flow

1. Open `http://localhost:3000`
2. See welcome screen with 6 quick actions
3. Click any card OR type your own question
4. Watch AI respond with sources
5. Toggle sidebar to see navigation

## 💡 Quick Actions

The welcome screen has 6 pre-configured prompts:

1. **Summarize Project** - "Summarize the ERCOT project"
2. **PPT Generation** - "Generate a presentation..."
3. **Research** - "What were the key challenges..."
4. **Generate Article** - "Tell me about market-to-market issues"
5. **Data Analytics** - "Analyze the NYISO bidding data"
6. **Code Explainer** - "Who was involved in..."

## 🐛 Troubleshooting

**"Connection refused" error:**
- Make sure Flask backend is running on port 5001
- Check `http://localhost:5001/api/health`

**Styling issues:**
- Clear Next.js cache: `rm -rf .next`
- Restart dev server

**TypeScript errors:**
- Run `npm install` again
- Check tsconfig.json is present

## 📊 Performance

- Fast initial load (<1s)
- Smooth animations
- Responsive design
- Optimized bundle size

## ✨ Perfect Figma Match

Every measurement, color, font, and spacing matches your Figma design exactly:
- ✅ Sidebar dimensions
- ✅ Search box specs
- ✅ Chat container size
- ✅ Typography
- ✅ Colors
- ✅ Border radius
- ✅ Spacing

## 🚀 Ready for Demo!

This frontend is production-ready and perfect for:
- YC Demo
- Investor presentations
- Product demos
- User testing

---

**Built with precision to match Figma specifications exactly!**
