import { Box, Flex, Button, Heading } from '@chakra-ui/react'
import { Link as RouterLink } from 'react-router-dom'

export default function NavBar() {
  return (
    <Box as="nav" bg="blue.600" color="white" px={8} py={4} role="navigation" aria-label="Main navigation">
      <Flex justify="space-between" align="center" maxW="1200px" mx="auto">
        <Heading as="h1" size="lg">
          NPM Registry
        </Heading>
        <Flex gap={4}>
          <Button as={RouterLink} to="/" variant="ghost" colorScheme="whiteAlpha" aria-label="Home">
            Home
          </Button>
          <Button as={RouterLink} to="/directory" variant="ghost" colorScheme="whiteAlpha" aria-label="Directory">
            Directory
          </Button>
          <Button as={RouterLink} to="/upload" variant="ghost" colorScheme="whiteAlpha" aria-label="Upload Package">
            Upload
          </Button>
          <Button as={RouterLink} to="/rate" variant="ghost" colorScheme="whiteAlpha" aria-label="Rate Package">
            Rate
          </Button>
          <Button as={RouterLink} to="/admin" variant="ghost" colorScheme="whiteAlpha" aria-label="Admin">
            Admin
          </Button>
        </Flex>
      </Flex>
    </Box>
  )
}

