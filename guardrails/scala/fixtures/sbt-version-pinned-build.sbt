ThisBuild / scalaVersion := "3.4.1"
ThisBuild / organization := "io.company"

lazy val core = (project in file("core"))
  .settings(
    libraryDependencies ++= Seq(
      "org.typelevel" %% "cats-effect" % "3.5.4",
      "org.scalameta" %% "munit" % "1.0.0" % Test
    )
  )
