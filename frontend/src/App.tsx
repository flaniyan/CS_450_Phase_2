import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Box } from '@chakra-ui/react'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import Directory from './pages/Directory'
import Upload from './pages/Upload'
import Rate from './pages/Rate'
import Admin from './pages/Admin'

function App() {
  return (
    <Router>
      <Box minH="100vh" bg="gray.50">
        <NavBar />
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/directory" element={<Directory />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/rate" element={<Rate />} />
          <Route path="/admin" element={<Admin />} />
        </Routes>
      </Box>
    </Router>
  )
}

export default App

