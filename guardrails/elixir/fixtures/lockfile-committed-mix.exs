defmodule Widget.MixProject do
  use Mix.Project

  def project do
    [
      app: :widget,
      version: "1.2.3",
      elixir: "~> 1.16",
      deps: deps()
    ]
  end

  defp deps do
    [
      {:phoenix, "~> 1.7.11"},
      {:jason, "~> 1.4"}
    ]
  end
end
