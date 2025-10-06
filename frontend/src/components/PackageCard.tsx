import { Box, Heading, Text, Button, HStack } from '@chakra-ui/react'
import { Package } from '../services/api'

interface PackageCardProps {
  package: Package
  onDownload?: () => void
}

export default function PackageCard({ package: pkg, onDownload }: PackageCardProps) {
  return (
    <Box p={5} shadow="md" borderWidth="1px" borderRadius="lg" bg="white">
      <Heading as="h3" size="md" mb={2}>
        {pkg.name}
      </Heading>
      <Text color="gray.600" mb={3}>
        Version: {pkg.version}
      </Text>
      <HStack>
        <Button size="sm" colorScheme="blue" onClick={onDownload} aria-label={`Download ${pkg.name}`}>
          Download
        </Button>
      </HStack>
    </Box>
  )
}

