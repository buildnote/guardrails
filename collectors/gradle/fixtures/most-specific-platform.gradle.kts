
                dependencies {
                    implementation(platform("com.company:company-bom:1.0.0"))
                    implementation(enforcedPlatform("com.company.data:data-bom:2.0.0"))

                    implementation("com.company.data:store")
                    implementation("com.company.web:server")
                    implementation("com.company.data:cache:9.9.9")
                }
            