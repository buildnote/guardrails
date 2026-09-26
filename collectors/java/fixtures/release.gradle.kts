plugins {
    java
}

tasks.withType<JavaCompile> {
    options.release.set(21)
}
