import { useState } from 'react'
import { Container, Heading, VStack, Button, Text, useToast, Alert, AlertIcon } from '@chakra-ui/react'
import { packageAPI } from '../services/api'

export default function Admin() {
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset the registry? This action cannot be undone.')) {
      return
    }

    setLoading(true)
    try {
      await packageAPI.reset()
      toast({
        title: 'Registry reset successfully',
        status: 'success',
        duration: 3000,
      })
    } catch (error) {
      toast({
        title: 'Reset failed',
        status: 'error',
        duration: 3000,
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Container maxW="container.md" py={10}>
      <VStack spacing={6} align="stretch">
        <Heading as="h1" size="xl">
          Admin Panel
        </Heading>
        <Alert status="warning">
          <AlertIcon />
          This action will reset the entire registry system state.
        </Alert>
        <Text>
          Use this button to reset the package registry to its initial state. 
          All packages and data will be removed.
        </Text>
        <Button 
          colorScheme="red" 
          onClick={handleReset} 
          isLoading={loading}
          aria-label="Reset registry"
        >
          Reset Registry
        </Button>
      </VStack>
    </Container>
  )
}

