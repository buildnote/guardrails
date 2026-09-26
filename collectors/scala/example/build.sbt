ThisBuild / scalaVersion := "3.4.1"
ThisBuild / organization := "io.company"

lazy val core = (project in file("core"))
  .settings(
    libraryDependencies ++= Seq(
      "org.typelevel" %% "cats-effect" % "3.5.4",
      "com.lihaoyi" %% "upickle" % "3.3.0"
    )
  )

lazy val server = (project in file("server"))
  .dependsOn(core)
  .settings(
    libraryDependencies ++= Seq(
      "org.http4s" %% "http4s-ember-server" % "0.23.27",
      "org.scalameta" %% "munit" % "1.0.0" % Test
    )
  )
