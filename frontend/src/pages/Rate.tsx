import { useState } from 'react'
import { Container, Heading, VStack, Input, Button, useToast } from '@chakra-ui/react'
import { packageAPI, PackageRating } from '../services/api'
import MetricChart from '../components/MetricChart'

export default function Rate() {
  const [packageName, setPackageName] = useState('')
  const [rating, setRating] = useState<PackageRating | null>(null)
  const [loading, setLoading] = useState(false)
  const toast = useToast()

  const handleRate = async () => {
    if (!packageName) {
      toast({
        title: 'Please enter a package name',
        status: 'warning',
        duration: 3000,
      })
      return
    }

    setLoading(true)
    try {
      const response = await packageAPI.rate(packageName)
      setRating(response.data)
    } catch (error) {
      toast({
        title: 'Failed to fetch rating',
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
          Rate Package
        </Heading>
        <Input
          placeholder="Enter package name"
          value={packageName}
          onChange={(e) => setPackageName(e.target.value)}
          aria-label="Package name"
        />
        <Button 
          colorScheme="blue" 
          onClick={handleRate} 
          isLoading={loading}
          aria-label="Get package rating"
        >
          Get Rating
        </Button>
        {rating && <MetricChart rating={rating} />}
      </VStack>
    </Container>
  )
}

