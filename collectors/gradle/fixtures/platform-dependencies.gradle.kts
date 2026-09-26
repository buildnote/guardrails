
                dependencies {
                    testImplementation(platform("org.junit:junit-bom:6.0.3"))
                    testImplementation(platform("org.http4k:http4k-bom:6.57.2.0"))

                    testImplementation("org.junit.jupiter:junit-jupiter-api")
                    testImplementation("org.junit.platform:junit-platform-launcher")
                    testImplementation("org.http4k:http4k-testing-approval")
                    testImplementation("com.unmanaged:widget")
                }
            