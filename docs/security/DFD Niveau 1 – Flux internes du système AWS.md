flowchart TD
A[Utilisateur / Développeur ACME]
B[API Gateway / Interface Web]
C[Service d'Application - ECS Fargate (FastAPI)]
D[S3 - Stockage des packages ZIP]
E[DynamoDB - Métadonnées et scores]
F[Bedrock / LLM - Analyse]
G[CloudWatch - Logs et Surveillance]
H[KMS - Gestion des clés]

    %% Flux
    A -->|1. Authentification (JWT via Cognito)| B
    B -->|2. Requête API REST (upload / score / get)| C
    C -->|3. Évaluation du modèle + calcul métriques| E
    C -->|4. Sauvegarde artefact ZIP| D
    C -->|5. Journalisation et métriques| G
    C -->|6. Chiffrement / Déchiffrement des données| H
    C -->|7. Appel d’un modèle LLM pour analyse README| F
    E -->|8. Résultat : métadonnées + NetScore| B
    D -->|9. Téléchargement du package demandé| B
    B -->|10. Réponse complète JSON / fichier| A
