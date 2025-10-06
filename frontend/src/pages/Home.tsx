import { Box, Container, Heading, Text, VStack, Button } from '@chakra-ui/react'
import { Link as RouterLink } from 'react-router-dom'

export default function Home() {
  return (
    <Container maxW="container.lg" py={10}>
      <VStack spacing={6} align="start">
        <Box as="header">
          <Heading as="h1" size="2xl" mb={4}>
            Welcome to NPM Registry
          </Heading>
          <Text fontSize="lg" color="gray.600">
            A trustworthy package management system with built-in quality metrics
          </Text>
        </Box>

        <Box as="main">
          <Heading as="h2" size="lg" mb={3}>
            Features
          </Heading>
          <VStack align="start" spacing={3}>
            <Text>📦 Upload and manage package files</Text>
            <Text>⭐ Check package ratings and quality metrics</Text>
            <Text>🔍 Search and download packages</Text>
            <Text>🛡️ ADA-compliant and accessible interface</Text>
          </VStack>

          <VStack mt={8} spacing={4} align="start">
            <Button as={RouterLink} to="/directory" colorScheme="blue" size="lg">
              Browse Directory
            </Button>
            <Button as={RouterLink} to="/upload" colorScheme="green" size="lg">
              Upload Package
            </Button>
          </VStack>
        </Box>
      </VStack>
    </Container>
  )
}

