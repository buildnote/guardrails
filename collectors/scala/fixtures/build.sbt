ThisBuild / scalaVersion := "3.4.1"

lazy val core = (project in file("core"))
  .settings(
    libraryDependencies ++= Seq(
      "org.typelevel" %% "cats-effect" % "3.5.4",
      "org.postgresql" % "postgresql" % "42.7.3",
      "com.company" %% "queue" % queueVersion
    )
  )

lazy val server = (project in file("server"))
  .settings(
    libraryDependencies ++= Seq(
      "org.scalameta" %% "munit" % "1.0.0" % Test,
      "org.slf4j" % "slf4j-api" % "2.0.13" % "provided"
      // "com.evil" %% "commented" % "1.0.0"
    )
  )
