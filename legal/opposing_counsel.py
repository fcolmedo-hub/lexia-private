class OpposingCounselEngine:
    def review(self, thesis: str, facts: str, draft: str) -> dict:
        attacks = [
            "Cuestionar que la conclusión se derive de los hechos relatados.",
            "Discutir la aplicabilidad de las fuentes por diferencias "
            "fácticas, jurisdiccionales o temporales.",
            "Señalar que una opinión doctrinaria no equivale necesariamente "
            "a una regla obligatoria.",
        ]

        if len(draft.strip()) < 1500:
            attacks.append(
                "Alegar insuficiencia de desarrollo y ausencia de los "
                "pasos intermedios del razonamiento."
            )

        if not facts.strip():
            attacks.append(
                "Atacar el planteo por abstracción y falta de base fáctica."
            )

        return {
            "attacks": attacks,
            "procedural": [
                "Revisar competencia, legitimación y oportunidad procesal.",
                "Plantear falta de prueba de los hechos constitutivos.",
                "Objetar citas incompletas o descontextualizadas.",
            ],
            "questions": [
                "¿Qué documento acredita cada hecho central?",
                "¿Qué hecho omitido podría favorecer a la contraparte?",
                "¿La cronología es compatible con los plazos invocados?",
                "¿Los daños o montos fueron acreditados y cuantificados?",
            ],
            "reinforcement": [
                "Crear una matriz hecho–prueba–consecuencia.",
                "Incorporar y distinguir el mejor precedente adverso.",
                "Verificar cada fuente y usar solo el pasaje necesario.",
                "Alinear la conclusión con una petición concreta.",
            ],
        }
