
                dependencies {
                    implementation("org.slf4j:slf4j-api:1.7.36")
                    testImplementation(platform("org.junit:junit-bom:5.11.0"))
                    api(project(":service"))
                    implementation(kotlin("stdlib"))
                }
            